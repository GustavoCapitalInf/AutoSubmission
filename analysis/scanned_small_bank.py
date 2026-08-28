from __future__ import annotations

import re
from datetime import date, timedelta

from .date_tokens import date_refusal, iso_or_none
from .money import money_refusal, parse_money
from .parser_registry import make_detector, required
from .schema import Statement, StatementDailyBalance, Transaction
from .tables import compact_whitespace, unique_match
from .td_can import normalize_mojibake


_MONTH_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})")
_MONEY_TOKEN_RE = re.compile(r"\$?\s*\d[\d,]*\.\d{2}")
#: Account-holder line inside the first page's address block: a name carrying
#: a business-entity suffix (structural marker - never a memorized customer
#: name, R-1 item 2).
_HOLDER_NAME_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9&'.\- ]{1,60}?,?\s*"
    r"(?:LLC|L\.L\.C\.|INC|CORP|LTD|LLP|PLLC|COMPANY|ENTERPRISES)\b\.?)",
    re.IGNORECASE,
)
#: Check-image caption printed alongside the scanned check: independent
#: in-document evidence of a check's true amount (R-1 item 1).
_CHECK_CAPTION_RE = re.compile(
    r"Number:\s*(\d{3,})\s+Date:\s*(\d{1,2}/\d{1,2}/\d{2,4})\s+"
    r"Amount:\s*\$?\s*(\d[\d,]*(?:\.\d{2})?)",
    re.IGNORECASE,
)


def _extract_holder_name(markdown: str) -> str | None:
    """Business-entity-suffixed name from the first page's header block."""
    first_page = re.split(r"--- Page 2 ---", markdown, maxsplit=1)[0]
    for line in first_page.splitlines():
        match = _HOLDER_NAME_RE.search(line)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()
    return None


def _money(value: str) -> float:
    parsed = parse_money(value.replace("$", "").strip())
    if parsed is None:
        # RAISE-PRIVACY-3 (#HYGIENE8), W3 §PRIVACY3 P10 item 2. The refusal is
        # still a `ValueError` - four `except ValueError` handlers in this
        # module catch this function and `_iso` below, so the CLASS is part of
        # the contract - but the printed cell no longer travels in it.
        raise money_refusal("scanned_small_bank._money", value)
    return parsed


def _iso(value: str) -> str:
    m = _MONTH_RE.fullmatch(value.strip())
    if not m:
        # A DATE cell, so the date grammar's constructor rather than the money
        # one; same class, same handlers, no token in the message.
        raise date_refusal("scanned_small_bank._iso", value)
    month, day, raw_year = m.groups()
    year = int(raw_year)
    if year < 100:
        year += 2000
    # THE SECOND LEAK IN THIS FUNCTION, found by driving the poison set at it
    # rather than by reading the ledger: `_MONTH_RE` proves a token's SHAPE and
    # nothing more, so `99/01/26` and `02/30/26` match it and reach `date()` -
    # which echoes the offending number ("month must be in 1..12, not 99",
    # "day 30 must be in range 1..28 for month 2 in year 2026"). The printed
    # month, day and year travelled out of the parser in a message §PRIVACY3's
    # ledger never named, because there is no `raise` here to grep for.
    # `iso_or_none` is the shared funnel for exactly this ("a row-date regex
    # proves a token's shape and nothing more"); the refusal is raised OUTSIDE
    # it, so nothing is chained.
    iso = iso_or_none(year, int(month), int(day))
    if iso is None:
        raise date_refusal("scanned_small_bank._iso", value)
    return iso


def _date_from_mdyy(value: str, *, year: int) -> str:
    # REVIEW MAJOR-2, `_iso`'s leak standing again twenty lines below the fix:
    # the caller's `(\d{1,2}/\d{2})` proves the token's SHAPE and nothing more,
    # so a row printed `13/40` reaches `date()`, whose ValueError echoes the
    # printed month. Same funnel and same refusal as `_iso` above, raised from
    # OUTSIDE the funnel, and still a `ValueError` so the four handlers in this
    # module keep catching it.
    month, day = [int(part) for part in value.split("/", 1)]
    iso = iso_or_none(year, month, day)
    if iso is None:
        raise date_refusal("scanned_small_bank._date_from_mdyy", value)
    return iso


def _daily_balances(markdown: str) -> dict[str, float]:
    start = re.search(r"DAILY BALANCE (?:SUMMARY|INFORMATION)\b", markdown, re.IGNORECASE)
    if not start:
        return {}
    block = markdown[start.end():]
    block = re.split(
        r"(?i)(?:SUMMARY OF FEES|--- Page|\*\*\*|Member\s+FDIC|TOTAL YEAR TO DATE)",
        block,
        maxsplit=1,
    )[0]
    balances: dict[str, float] = {}
    statement_year = None
    year_match = re.search(r"\b\d{1,2}/\d{1,2}/(\d{2,4})\b", markdown)
    if year_match:
        statement_year = int(year_match.group(1))
        if statement_year < 100:
            statement_year += 2000
    for raw_date, amount in re.findall(r"(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s+(\d[\d,]*\.\d{2})", block):
        try:
            if raw_date.count("/") == 1 and statement_year is not None:
                raw_date = f"{raw_date}/{statement_year}"
            balances[_iso(raw_date)] = _money(amount)
        except ValueError:
            continue
    return balances


def _attach_daily_balances(txns: list[Transaction], balances: dict[str, float]) -> list[Transaction]:
    if not balances:
        return txns
    last_idx_by_date: dict[str, int] = {}
    for idx, txn in enumerate(txns):
        if txn.date in balances:
            last_idx_by_date[txn.date] = idx
    out = list(txns)
    for txn_date, idx in last_idx_by_date.items():
        out[idx] = out[idx].model_copy(update={"running_balance": balances[txn_date]})
    return out


def _sort_txns(txns: list[Transaction]) -> list[Transaction]:
    return sorted(txns, key=lambda t: (t.date, 0 if t.amount > 0 else 1, t.description))


def _section(markdown: str, start: str, stop: str) -> str:
    match = re.search(
        rf"(?:{start})(.*?)(?:{stop})",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    return match.group(1) if match else ""


def _parse_date_amount_description_rows(block: str, *, sign: int) -> list[Transaction]:
    txns: list[Transaction] = []
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = re.match(r"^(\d{1,2}/\d{1,2}/\d{4})\s+(\d[\d,]*\.\d{2})\s+(.+)$", line)
        if not m:
            i += 1
            continue
        txn_date, amount, desc = m.groups()
        desc_parts = [desc.strip()]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if not nxt or re.match(r"^\d{1,2}/\d{1,2}/\d{4}\s+\d[\d,]*\.\d{2}\b", nxt):
                break
            if re.search(r"^(?:DATE|TOTAL|DAILY BALANCE|SERVICE CHARGE ANALYSIS|SUMMARY OF FEES)\b", nxt, re.IGNORECASE):
                break
            desc_parts.append(nxt)
            i += 1
        signed = round(abs(_money(amount)) * sign, 2)
        txns.append(Transaction(
            date=_iso(txn_date),
            description=compact_whitespace(" ".join(desc_parts)),
            amount=signed,
            direction="credit" if signed > 0 else "debit",
        ))
    return txns


def _parse_two_column_date_amount_desc(block: str, *, sign: int) -> list[Transaction]:
    txns: list[Transaction] = []
    pattern = re.compile(
        r"(\d{1,2}/\d{1,2}/\d{4})\s+(\d[\d,]*\.\d{2})\s+"
        r"(.+?)(?=(?:\s+\d{1,2}/\d{1,2}/\d{4}\s+\d[\d,]*\.\d{2})|$)",
        re.DOTALL,
    )
    for txn_date, amount, desc in pattern.findall(compact_whitespace(block)):
        signed = round(abs(_money(amount)) * sign, 2)
        txns.append(Transaction(
            date=_iso(txn_date),
            description=compact_whitespace(desc),
            amount=signed,
            direction="credit" if signed > 0 else "debit",
        ))
    return txns


def _parse_checks(block: str, *, sign: int = -1) -> list[Transaction]:
    txns: list[Transaction] = []
    # Real dash characters only - the input is mojibake-normalized first
    # (R-1 item 11; the class previously carried raw mojibake bytes).
    for check_no, raw_date, amount in re.findall(
        r"\b(\d{3,})\s+\*?\s*[—–\- ]*\s*(\d{1,2}/\d{1,2}/\d{4})\s+(\d[\d,]*\.\d{2})",
        block,
    ):
        signed = round(abs(_money(amount)) * sign, 2)
        txns.append(Transaction(
            date=_iso(raw_date),
            description=f"Check {check_no}",
            amount=signed,
            direction="credit" if signed > 0 else "debit",
        ))
    return txns


def _discard_inconsistent_ocr_balances(
    stmt: Statement,
    txns: list[Transaction],
) -> list[Transaction]:
    """Ignore an OCR balance grid only after the line-item ledger proves complete."""
    if not any(txn.running_balance is not None for txn in txns):
        return txns
    required = (
        stmt.beginning_balance,
        stmt.ending_balance,
        stmt.stated_credit_count,
        stmt.stated_debit_count,
        stmt.stated_total_credits,
        stmt.stated_total_debits,
    )
    if any(value is None for value in required):
        return txns

    credits = [txn for txn in txns if txn.amount > 0]
    debits = [txn for txn in txns if txn.amount < 0]
    detail_matches_summary = (
        len(credits) == stmt.stated_credit_count
        and len(debits) == stmt.stated_debit_count
        and abs(sum(txn.amount for txn in credits) - stmt.stated_total_credits) <= 0.01
        and abs(abs(sum(txn.amount for txn in debits)) - stmt.stated_total_debits) <= 0.01
        and abs(
            stmt.beginning_balance
            + sum(txn.amount for txn in txns)
            - stmt.ending_balance
        ) <= 0.01
    )
    if not detail_matches_summary:
        return txns

    expected = stmt.beginning_balance
    for txn in txns:
        expected = round(expected + txn.amount, 2)
        if txn.running_balance is not None and abs(expected - txn.running_balance) > 0.01:
            return [
                row.model_copy(update={"running_balance": None})
                for row in txns
            ]
    return txns


def detection_text(markdown: str) -> str:
    """The text these parsers recognise themselves in: scanned sources arrive
    with double-encoded accents, so repair them before matching."""
    return normalize_mojibake(markdown).upper()


#: The issuer's own masthead plus three ROW LABELS of the `ACCOUNT SUMMARY`
#: grid this parser reads.
#:
#: What they replace was an ACCOUNT TITLE: not a product line, but the name one
#: customer gave one of its accounts, printed in its address block and on the
#: face of its cheques. The same customer's other account carries a different
#: title and a third carries none at all, while the product line all nine of
#: these statements print is one of two ordinary business-checking names. So
#: the gate was the R-4b class exactly — a customer's own words standing in for
#: the issuer's — and it is now recorded there, in `REMOVED_LITERALS` in
#: `tests/test_no_statement_hardcodes.py`, which is the file that may name it
#: and this one is not. It claimed three of the nine statements this issuer
#: prints in the archive while the reader could see the other six perfectly
#: well.
#:
#: The grid's HEADING went with it, for a different reason: it is one line of
#: large print, and on one archive statement the scan destroyed it while
#: leaving every row of the grid beneath it legible. The row labels are what
#: `_southside_summary` actually reads, so the detector now claims exactly what
#: the parser can read.
#:
#: Measured over all 3,380 documents of the run of record: this set claims the
#: nine Southside statements, `parse_southside_scanned_statement` returns a
#: statement for all nine, and nothing else in the archive is claimed.
SOUTHSIDE_DETECTION_MARKERS = (
    required("bank_name", lambda t: "SOUTHSIDE" in t),
    required("credit_row", lambda t: "DEPOSITS/CREDITS" in t),
    required("debit_row", lambda t: "CHECKS/DEBITS" in t),
    required("period_row", lambda t: "DAYS IN STATEMENT PERIOD" in t),
)

APEX_DETECTION_MARKERS = (
    required("product", lambda t: "SUMMIT BUSINESS CHECKING" in t),
    required("opening_label", lambda t: "BALANCE FORWARD FROM" in t),
    required("closing_label", lambda t: "ENDING BALANCE AS OF" in t),
)

detect_southside = make_detector(SOUTHSIDE_DETECTION_MARKERS, detection_text)
detect_apex = make_detector(APEX_DETECTION_MARKERS, detection_text)


#: One money cell of this issuer's print, decimal point INCLUDED as a class.
#: See `_southside_money` for why the comma belongs in it.
_SS_MONEY = r"\d[\d,]*[.,]\d{2}"

#: Where each printed grid begins, and everything that ends one.
#:
#: The old boundaries were a heading spelled exactly and, for the withdrawals
#: grid, the literal page separator `--- Page 2 ---`. Both fail on a
#: photograph, in opposite directions and both silently:
#:
#: * a one-page statement HAS no `--- Page 2 ---`, so the withdrawals grid ran
#:   to the end of `_section`'s failed search and came back empty — two printed
#:   withdrawals read as none;
#: * a two-page statement has one in the wrong place, so the grid ran INTO the
#:   `DAILY BALANCE SUMMARY` beneath it and a daily-balance cell was published
#:   as a withdrawal (`debit_coverage` 1.248 on one archive statement, which is
#:   a reader inventing money);
#: * and a four-page statement whose withdrawals continue on sheet 2 lost every
#:   row after the break.
#:
#: A grid ends where the NEXT GRID begins. That is a fact about the printed
#: page rather than about the pagination, so it holds however the scan
#: paginates, and it is what these anchors express: each named grid runs from
#: the end of its own heading to the start of whichever anchor comes next,
#: named or terminal. Continuation pages carry no heading of their own — the
#: bank reprints only the column header — so they fall inside the span they
#: belong to without a rule of their own.
#:
#: The headings are matched on the WORDS that survive rather than on the
#: asterisks that do not: `*** WITHDRAWALS ***`, `[eee *** WITHDRAWALS **` and
#: `: ?WITHDRAWALS *** Sos .` are one heading photographed three times. A
#: heading line is required to carry a rule glyph and, being a heading, it
#: never carries a dated row.
_SS_ANCHORS = (
    ("deposits", r"(?im)^(?=[^\n]*\*)[^\n]*\bDEPOSITS\b[^\n]*$"),
    ("withdrawals", r"(?im)^(?=[^\n]*\*)[^\n]*\bWITHDRAWALS\b[^\n]*$"),
    (
        "checks",
        r"(?im)^[^\n]*(?:SUMMARY BY CHECK NUMBER|Listed in numerical order"
        r"|Date\s+Check\s+Number\s+Amount)[^\n]*$",
    ),
    ("daily", r"(?im)^[^\n]*(?:DAILY BALANCE SUMMARY|Date\s+Balance\s+Date)[^\n]*$"),
    # Terminal furniture: the cheque-image sheets and the footnote under the
    # cheque grid. Nothing after one of these belongs to the grid above it.
    (
        None,
        r"(?im)^[^\n]*(?:Denotes missing check numbers|Southside Bank\s+Page:"
        r"|SUBSTITUTE IMAGE|DEPOSIT TICKET|Credit DDA Deposit|ACCOUNT SUMMARY)[^\n]*$",
    ),
)


def _southside_grids(markdown: str) -> dict[str, str]:
    """The four printed grids, each running to wherever the next one starts."""
    marks: list[tuple[int, int, str | None]] = []
    for name, pattern in _SS_ANCHORS:
        for match in re.finditer(pattern, markdown):
            marks.append((match.start(), match.end(), name))
    # Ordered by POSITION alone. Sorting the whole tuple falls through to the
    # third element whenever two anchors match at the same offsets, and that
    # element is `None` for the terminal ones — `None < str` is a TypeError,
    # which the pipeline turns into a parser crash. Two anchors on one line is
    # not hypothetical here: this template prints `Southside Bank  Page:` on
    # its own line on six of the nine archive statements, and an OCR line-merge
    # with the `DAILY BALANCE SUMMARY` heading above it is one bad scan away.
    # A crash is a worse answer than a decline, and neither is what this input
    # deserves — the grids are well defined however the marks tie.
    marks.sort(key=lambda mark: (mark[0], mark[1]))
    grids = {"deposits": "", "withdrawals": "", "checks": "", "daily": ""}
    for index, (_start, end, name) in enumerate(marks):
        stop = marks[index + 1][0] if index + 1 < len(marks) else len(markdown)
        if name is not None:
            grids[name] += markdown[end:stop] + "\n"
    return grids


def _southside_day(token: str, period: tuple[str, str]) -> str | None:
    """One date cell, read strictly; `None` where the scan did not leave one.

    The cell the bank prints is `m/dd`. What arrives is that, or that with the
    solidus lost (`413`), or with the solidus resolved as a digit (`4101`,
    `4/17` printed as `47`), or as letters (`ANT`). This reader does not repair
    a cell: it enumerates the readings that are POSSIBLE for the statement's
    own period and accepts one only when exactly one exists. A cell with two
    readings, or none, is not a date and its row is dropped rather than dated
    by preference.
    """
    start, end = (date.fromisoformat(value) for value in period)
    candidates: set[date] = set()

    def admit(month: int, day: int) -> None:
        # The cell carries no year, so BOTH years the period touches are
        # offered and the period decides. On this template's own printing the
        # two are the same year and the second offer changes nothing; a period
        # the scan damaged into spanning a new year would otherwise silently
        # drop every row on the far side of it, which is the failure this
        # enumeration exists to refuse. Ambiguity between the two is resolved
        # the way every other ambiguity here is: not at all.
        for year in {start.year, end.year}:
            try:
                candidate = date(year, month, day)
            except ValueError:
                continue
            if start <= candidate <= end:
                candidates.add(candidate)

    canonical = re.fullmatch(r"(\d{1,2})/(\d{1,2})", token)
    if canonical:
        admit(int(canonical.group(1)), int(canonical.group(2)))
        return candidates.pop().isoformat() if len(candidates) == 1 else None
    if not re.fullmatch(r"\d{3,4}", token):
        # A TWO-glyph residue is not a date cell, however readable it looks.
        # This template zero-pads the day in every cell it prints — `4/01`,
        # `4/07`, `4/15`, never `4/7` — so `47` cannot be a whole cell that
        # merely lost its solidus. It is `4/17` with two glyphs gone, or
        # `4/07`, or `4/27`, and there is nothing in the token to say which.
        # Reading it as `4/7` looked unique and was WRONG on an archive
        # statement: the row belonged to the 17th, which the daily grid and
        # the day's own cheques both witness. Two glyphs, no date.
        return None
    for cut in (1, 2):
        if len(token) - cut == 2:
            admit(int(token[:cut]), int(token[cut:]))
    # The solidus resolved as a digit: `4101` for `4/01`, `4724` for `4/24`.
    # Only `1` and `7` are admitted because those are the glyphs a solidus can
    # be confused with; and, like every other reading, this one survives only
    # if it is the sole candidate.
    if len(token) == 4 and token[1] in "17":
        admit(int(token[0]), int(token[2:]))
    return candidates.pop().isoformat() if len(candidates) == 1 else None


def _southside_daily_cells(
    daily_grid: str, period: tuple[str, str]
) -> dict[str, set[float]]:
    """The printed daily-balance grid as `day -> every distinct balance printed
    for it`.

    One reading of this grid, used for two different things. A day the grid
    NAMES is a day the account moved, whatever balance the cell carries — that
    is what corroborates a reconstructed date. A day whose cell carries ONE
    balance is additionally an amount oracle. The two are separated here rather
    than conflated because they fail differently: a cell printed twice with two
    values still names its day, and it is on one archive statement of the nine
    (W3 §SCANHYG).
    """
    cells: dict[str, set[float]] = {}
    for token, amount in re.findall(
        r"([A-Za-z0-9/]{2,5})\s+(" + _SS_MONEY + r")", daily_grid
    ):
        day = _southside_day(token, period)
        value = _southside_money(amount)
        if day is None or value is None:
            continue
        cells.setdefault(day, set()).add(round(value, 2))
    return cells


def _southside_posted_days(daily_grid: str, period: tuple[str, str]) -> frozenset[str]:
    """Every day the printed daily-balance grid names.

    The grid prints an end-of-day balance for each day the account MOVED, so a
    day it does not name is a day on which no row was posted. That makes it the
    corroboration a reconstructed date needs and a canonical one does not: a
    cell the scan damaged may only be read as a day the bank itself says had
    activity.
    """
    return frozenset(_southside_daily_cells(daily_grid, period))


def _southside_money(token: str) -> float | None:
    """A money cell, with the decimal separator read from the token's shape.

    A photograph of this template resolves the decimal point as a comma often
    enough to matter (`9,000,00`, `225,00`, `2,549,33`). That is not read as a
    preference for one separator: a thousands group is THREE digits, so a comma
    followed by exactly two digits at the END of a token cannot be one, and the
    token has therefore told us which glyph it is. Where the shape is
    ambiguous — `1,234` — nothing is decided and the shared grammar answers.
    """
    return parse_money(re.sub(r",(\d{2})$", r".\1", token.strip()))


#: HORIZONTAL whitespace only. Every row of this grid is printed on one line,
#: and `\s` matches a newline: a pattern built with it would let a figure from
#: the line below answer a label on the line above. The reader this replaces
#: searched each line separately and so could not do that; these patterns run
#: over the whole page through `unique_match`, and this class is what keeps the
#: guarantee.
_SS_H = r"[^\S\n]"

#: The labelled rows of the `ACCOUNT SUMMARY` grid, each as ONE pattern over
#: the whole page.
#:
#: `unique_match` (the shared helper, `analysis/tables.py`) is what reads them,
#: and the discipline is its docstring's: a row this grid prints TWICE with two
#: different values is the document contradicting itself about its own summary,
#: and there is no rule that says which printing to believe — taking the first
#: would be picking one. A repeat that AGREES is a page header doing its job
#: and is free corroboration.
#:
#: This reader used to take the first printing (`found.setdefault`).
#: `texas_first`, in this same module and the same wave lineage, already
#: refused the contradiction, and the two-account printing under one heading is
#: exactly what would produce one. Measured before the change over all nine
#: archive statements this issuer prints: NO label is printed with more than
#: one distinct value on any of them, so adopting the shared discipline moves
#: no document (W3 §SCANHYG).
_SS_PERIOD_RE = re.compile(
    rf"Statement Dates{_SS_H}+(\d{{1,2}}/\d{{1,2}}/\d{{2,4}}){_SS_H}+thru"
    rf"{_SS_H}+(\d{{1,2}}/\d{{1,2}}/\d{{2,4}})",
    re.IGNORECASE | re.MULTILINE,
)
_SS_DAYS_RE = re.compile(
    rf"Days in Statement Period{_SS_H}+(\d+)", re.IGNORECASE | re.MULTILINE
)
#: The two count/total rows. The count is the cell printed immediately BEFORE
#: the label and the total is the last cell on the line, which is why this one
#: is anchored at the line end.
_SS_COUNTED_ROWS = (
    ("credit", re.compile(
        rf"(\S+)?{_SS_H}*Deposits{_SS_H}*/{_SS_H}*Credits{_SS_H}+({_SS_MONEY}){_SS_H}*$",
        re.IGNORECASE | re.MULTILINE)),
    ("debit", re.compile(
        rf"(\S+)?{_SS_H}*Checks{_SS_H}*/{_SS_H}*Debits{_SS_H}+({_SS_MONEY}){_SS_H}*$",
        re.IGNORECASE | re.MULTILINE)),
)
#: The four single-figure rows. The first two are required by the grid's own
#: identity; the last two are optional and publish as unknown when the scan
#: took them, exactly as a count does.
_SS_FIGURE_ROWS = (
    ("previous", re.compile(rf"Previous Balance{_SS_H}+({_SS_MONEY})",
                            re.IGNORECASE | re.MULTILINE)),
    ("ending", re.compile(rf"Ending Balance{_SS_H}+({_SS_MONEY})",
                          re.IGNORECASE | re.MULTILINE)),
    ("service", re.compile(rf"Total Service Charge{_SS_H}+({_SS_MONEY})",
                           re.IGNORECASE | re.MULTILINE)),
    ("interest", re.compile(rf"Interest Paid{_SS_H}+({_SS_MONEY})",
                            re.IGNORECASE | re.MULTILINE)),
)


def _southside_summary(text: str) -> dict[str, object] | None:
    """The `ACCOUNT SUMMARY` grid, read as the LABELLED GRID it is printed as.

    What this replaces was one regex spanning all seven rows of the grid at
    once, with `\\D{0,8}` standing in for the furniture between them. Two things
    defeat that on a photographed statement, and both defeated it here:

    * the furniture is the page's rotated left-margin text, and Tesseract
      resolves those glyphs as digits as readily as letters (`2 17
      Checks/Debits`, `... 0.00 2 Interest Paid`). `\\D` excludes a digit by
      construction, so a single mis-resolved margin glyph took the whole
      summary down. It did so on four of the nine statements this issuer
      prints in the archive — including the one already claimed and declined.
    * one coupled regex fails as a unit. A grid whose seven rows are each
      labelled does not need to be read as one thing, and reading it row by
      row means a row the scan damaged costs that row and nothing else.

    The counts are the case in point. One statement prints `Q Checks/Debits
    0.00` — the digit `0` resolved as a letter — and its count is published as
    UNKNOWN rather than guessed, while every other figure on the row is read.
    Nothing infers the count from the total being `0.00`; that would be an
    inference, and this reader records measurements.

    The grid is accepted only if its own arithmetic closes:
    `previous + credits - debits == ending`, to the cent. It closes on all nine.

    EACH ROW IS READ ONCE, OVER THE WHOLE PAGE, THROUGH `unique_match`. A label
    the grid prints twice with two different values refuses the row rather than
    resolving it by order of appearance: see `_SS_PERIOD_RE` above for why, and
    `analysis/tables.py::unique_match` for the discipline this shares with the
    two core-processor templates and `texas_first`. A required row that refuses
    refuses the document; an optional one publishes as unknown, which is what
    this reader already does with a count whose digit did not survive.
    """
    found: dict[str, object] = {}
    period = unique_match(text, _SS_PERIOD_RE)
    if period is not None:
        found["start"], found["end"] = period.group(1), period.group(2)
    days = unique_match(text, _SS_DAYS_RE)
    if days is not None:
        found["days"] = int(days.group(1))
    for key, pattern in _SS_COUNTED_ROWS:
        row = unique_match(text, pattern)
        if row is None:
            continue
        count = row.group(1)
        # `isdecimal`, NOT `isdigit`. `str.isdigit()` is True for the
        # superscripts U+00B9 U+00B2 U+00B3 and `int()` rejects them, so a
        # scan that resolved this grid's count digit as a superscript raised
        # `ValueError` out of this parser instead of publishing the count as
        # unknown — the crash class `tests/test_parser_crash_shapes.py` exists
        # for, and one this reader is not entitled to when it already handles
        # a count whose digit became a LETTER. `isdecimal()` is exactly the set
        # `int()` accepts, so the conversion below is total.
        found[key + "_count"] = int(count) if count and count.isdecimal() else None
        found[key + "_total"] = _southside_money(row.group(2))
    for key, pattern in _SS_FIGURE_ROWS:
        figure = unique_match(text, pattern)
        if figure is not None:
            found[key] = _southside_money(figure.group(1))
    required_keys = ("start", "end", "days", "previous", "ending", "credit_total", "debit_total")
    if any(found.get(key) is None for key in required_keys):
        return None
    # A date cell the scan corrupted can still have the SHAPE of a date, and
    # `_iso` RAISES on one that is only shaped like it (`5/41/26`). A parser
    # that raises is a parser crash, and a crash is a worse answer than a
    # decline: this reader has no period it can trust, so it refuses. The
    # conversion belongs here rather than at the call site because this is the
    # only place the period is admitted, and every later reading — the year,
    # the candidate enumeration, the posted-day set — is bounded by it.
    for key in ("start", "end"):
        try:
            found[key] = _iso(str(found[key]))
        except ValueError:
            return None
    identity = (
        float(found["previous"])  # type: ignore[arg-type]
        + float(found["credit_total"])  # type: ignore[arg-type]
        - float(found["debit_total"])  # type: ignore[arg-type]
        - float(found["ending"])  # type: ignore[arg-type]
    )
    if abs(identity) > 0.01:
        return None
    return found


def parse_southside_scanned_statement(markdown: str) -> Statement | None:
    if not detect_southside(markdown).claims:
        return None
    markdown = normalize_mojibake(markdown)
    upper = markdown.upper()

    text = compact_whitespace(markdown)
    stmt = Statement(bank="Southside Bank", currency="USD",
                     currency_source="institution_default")
    # Digits must directly follow the label: an occurrence corrupted by stray
    # OCR quote glyphs is skipped in favor of a clean later occurrence
    # (R-1 item 11 - the previous class of mojibake quote characters never
    # matched real text and only obscured that behaviour).
    acct = re.search(r"Account Number\s+(\d+)", text, re.IGNORECASE)
    if acct:
        stmt.account_number = acct.group(1)
    # Holder from the entity-suffix structural marker, not a memorized
    # customer name (R-1 item 2).
    stmt.account_name = _extract_holder_name(markdown)
    summary = _southside_summary(markdown)
    if summary is None:
        return None
    # Already ISO, and already refused if the cell was not a date at all.
    stmt.period_start = str(summary["start"])
    stmt.period_end = str(summary["end"])
    stmt.beginning_balance = summary["previous"]  # type: ignore[assignment]
    stmt.ending_balance = summary["ending"]  # type: ignore[assignment]
    stmt.days_in_period = int(summary["days"])  # type: ignore[call-overload]
    stmt.stated_credit_count = summary["credit_count"]  # type: ignore[assignment]
    stmt.stated_debit_count = summary["debit_count"]  # type: ignore[assignment]
    stmt.stated_total_credits = summary["credit_total"]  # type: ignore[assignment]
    stmt.stated_total_debits = summary["debit_total"]  # type: ignore[assignment]
    stmt.stated_service_charge = summary.get("service")  # type: ignore[assignment]
    stmt.stated_interest_paid = summary.get("interest")  # type: ignore[assignment]

    year = int(stmt.period_end[:4])
    period = (stmt.period_start, stmt.period_end)
    grids = _southside_grids(markdown)
    posted = _southside_posted_days(grids["daily"], period)
    txns: list[Transaction] = []
    txns.extend(_parse_southside_line_rows(
        grids["deposits"], year=year, sign=1, period=period, posted=posted))
    txns.extend(_parse_southside_line_rows(
        grids["withdrawals"], year=year, sign=-1, period=period, posted=posted))
    txns.extend(_parse_southside_checks(
        grids["checks"], year=year, period=period, posted=posted))
    txns = _repair_checks_from_image_captions(markdown, txns, stmt)
    txns = _attach_daily_balances(_sort_txns(txns), _daily_balances(markdown))
    txns = _discard_inconsistent_ocr_balances(stmt, txns)
    if len(txns) < (stmt.stated_credit_count or 0):
        return None
    stmt.transactions = txns
    return stmt


#: The resolution of the span comparison below, and it is FLOAT NOISE and
#: nothing else. Both sides are figures already rounded to the cent — the
#: printed cell as the page prints it, the ledger step as `round(x, 2)` leaves
#: it — so two that agree differ by ~1e-13 at worst and two that disagree
#: differ by at least a cent. The floor was 0.01 until W3 §SCANHYG SH13
#: (review finding 5): it silenced a one-cent over-capture, which is the
#: smallest instance of the exact thing the check exists to find.
_GRID_CELL_EPSILON = 1e-6


def daily_grid_amount_contradictions(markdown: str, stmt: Statement) -> list[str]:
    """The printed daily-balance grid, held against the ledger as an AMOUNT
    oracle rather than only as a date one.

    THE GAP THIS CLOSES, and it is a gap in the reader's design rather than a
    residue. `_southside_posted_days` already consults this grid, and it
    consults it about DATES only: a reconstructed date must name a day the
    grid names. Nothing asked the grid what the day was WORTH. On one archive
    statement that cost a FOUR-FIGURE over-capture — a reader publishing more
    debit money than the bank states, which is worse in kind than publishing
    less, and which every other check on the document was blind to because the
    row it came from was otherwise perfectly formed (W3 §SCANFINISH SF2,
    carded there as SS-GRID-AMOUNTS). The size is stated as a CLASS here and
    in every comment of the four modules this card owns: the figure is the
    document's. The universal this sentence used to claim — "everywhere else
    in tracked source" — was not measured and is not true; what the whole
    tracked tree carries is the train's to sweep (W3 §SCANHYG SH13, review
    finding 1).

    WHAT THE GRID SAYS. It prints an end-of-day balance for each day the
    account moved, so consecutive printed cells partition the period: the step
    from one cell to the next is the bank's own statement of what the account
    did over the days BETWEEN them, including the days it did not print
    because nothing posted on them. The ledger's rows dated in that same span
    must move the same money. That is a per-span comparison and it localises:
    a span whose two readings agree is a span read correctly whatever the
    running error elsewhere is, which a cumulative walk cannot say.

    THE RESOLUTION IS ANY NON-ZERO DIFFERENCE. A span the grid and the ledger
    disagree about by ONE CENT is a contradiction and is reported: this check
    exists to find money the reader took that the bank did not print, and one
    cent of it is the smallest instance of that rather than a different kind of
    thing. `_GRID_CELL_EPSILON` is float noise between two figures already
    rounded to the cent and is not a tolerance for disagreement (W3 §SCANHYG
    SH3, review finding 5). The last-cell comparison at the end of this
    function holds two figures the BANK printed against each other, which is a
    different question, and this card's ruling scoped the change to the cell
    against the ledger; it stays at the cent.

    NEITHER READING IS PREFERRED AND NOTHING IS REPAIRED. The rows are the
    figures the bank printed and the cell is the figure the bank printed; only
    the bank can say which is wrong. The disagreement is reported — the same
    answer `columbia_bank.daily_grid_contradictions` gives for the same shape,
    and for the reason the repair doctrine gives: a parser that resolves this
    by rewriting an amount is a parser whose downstream gate is its own
    objective function.

    Re-read from the DOCUMENT, not taken from the statement, so the check keeps
    working against a reader that stops consulting the grid. Guarded by the
    registry like every other integrity check; total by construction, because a
    check that raises is a document routed to review for no finding.
    """
    if not stmt.period_start or not stmt.period_end or stmt.beginning_balance is None:
        return []
    try:
        start = date.fromisoformat(stmt.period_start)
        end = date.fromisoformat(stmt.period_end)
    except ValueError:
        return []
    if end < start:
        return []
    source = normalize_mojibake(markdown)
    cells = _southside_daily_cells(
        _southside_grids(source)["daily"], (stmt.period_start, stmt.period_end)
    )
    notes: list[str] = []
    printed: dict[date, float] = {}
    for iso, values in sorted(cells.items()):
        day = date.fromisoformat(iso)
        if not start <= day <= end:
            continue
        if len(values) > 1:
            # The grid contradicting ITSELF about one day. The day still counts
            # as one the account moved; the cell is not an oracle.
            notes.append(
                f"the daily-balance grid prints {len(values)} different balances for "
                f"{iso}, so the balance it states for that day is not readable"
            )
            continue
        printed[day] = next(iter(values))
    if not printed:
        return notes

    movement: dict[date, float] = {}
    for txn in stmt.transactions:
        try:
            when = date.fromisoformat(txn.date)
        except (TypeError, ValueError):
            # A ledger this reader cannot date is a ledger this check cannot
            # walk. It says so by saying nothing, which is what the guard
            # contract asks of an answer that is unknown.
            return notes
        movement[when] = round(movement.get(when, 0.0) + txn.amount, 2)

    previous_day, previous_balance = start - timedelta(days=1), stmt.beginning_balance
    for day in sorted(printed):
        moved, probe = 0.0, previous_day + timedelta(days=1)
        while probe <= day:
            moved = round(moved + movement.get(probe, 0.0), 2)
            probe += timedelta(days=1)
        step = round(printed[day] - previous_balance, 2)
        if abs(step - moved) > _GRID_CELL_EPSILON:
            span = (
                f"on {day.isoformat()}"
                if previous_day + timedelta(days=1) == day
                else f"from {(previous_day + timedelta(days=1)).isoformat()} to {day.isoformat()}"
            )
            notes.append(
                f"the daily-balance grid steps by {step:,.2f} {span} but the "
                f"transactions dated in that span move {moved:,.2f}"
            )
        previous_day, previous_balance = day, printed[day]

    # The grid's own last word against the summary's. Two printings of one
    # figure, and neither is derived from the other.
    if stmt.ending_balance is not None:
        last = printed[max(printed)]
        if abs(last - stmt.ending_balance) > 0.01:
            notes.append(
                f"the daily-balance grid's last printed cell is {last:,.2f} but the "
                f"summary states an ending balance of {stmt.ending_balance:,.2f}"
            )
    return notes


def _parse_two_column_mdyy_rows(block: str, *, year: int, sign: int) -> list[Transaction]:
    txns: list[Transaction] = []
    block = re.sub(r"(?i)\b(?:ae|if|cy|z)\s+(?=\d{1,2}/\d{2}\b)", " ", block)
    block = re.sub(r"[;:]\s+(?=\d{1,2}/\d{2}\b)", " ", block)
    pattern = re.compile(
        r"(\d{1,2}/\d{2})\s+(.+?)\s+(\d[\d,]*\.\d{2})(?=(?:\s+\d{1,2}/\d{2}\s)|$)",
        re.DOTALL,
    )
    for mmdd, desc, amount in pattern.findall(compact_whitespace(block)):
        signed = round(abs(_money(amount)) * sign, 2)
        txns.append(Transaction(
            date=_date_from_mdyy(mmdd, year=year),
            description=compact_whitespace(desc),
            amount=signed,
            direction="credit" if signed > 0 else "debit",
        ))
    return txns


def _southside_row_date(
    tokens: list[str], period: tuple[str, str], posted: frozenset[str]
) -> tuple[str, int] | None:
    """The row's date and the index after it, or `None`.

    Two passes, and the order is the point. A cell the bank printed CLEANLY is
    taken first, wherever on the line it stands, because the left margin of
    this template carries rotated page furniture that the scan drops into the
    row as one or two stray glyphs — and one of those glyphs can itself be a
    readable date (`47` is `4/7` in an April statement). Only when no clean
    cell exists is a damaged one reconstructed, and a reconstruction must
    additionally name a day the printed daily-balance grid names.
    """
    for index, token in enumerate(tokens):
        if re.fullmatch(r"\d{1,2}/\d{1,2}", token):
            day = _southside_day(token, period)
            if day is not None:
                return day, index + 1
    for index, token in enumerate(tokens):
        day = _southside_day(token, period)
        if day is not None and day in posted:
            return day, index + 1
    return None


def _parse_southside_line_rows(
    block: str,
    *,
    year: int,
    sign: int,
    period: tuple[str, str],
    posted: frozenset[str],
) -> list[Transaction]:
    """`date description amount` rows, one per line, amount last.

    What this replaces stripped a memorised list of OCR glyphs (`ae`, `if`,
    `cy`, `z`, `ee`, `a`) off the front of each line and then required the date
    to be the first thing left. That list is a reading of six statements rather
    than of the template, and a seventh photograph produces a seventh glyph.
    The structural statement is the one below: on a row of this grid the
    AMOUNT is the last cell and the DATE is the first cell that is a date; what
    stands before the date is margin ink and what stands between them is the
    description.
    """
    txns: list[Transaction] = []
    for raw in block.splitlines():
        line = raw.strip()
        amount = re.search(r"(" + _SS_MONEY + r")\s*$", line)
        if not amount:
            continue
        tokens = line[: amount.start()].split()
        found = _southside_row_date(tokens, period, posted)
        if found is None:
            continue
        day, after = found
        description = compact_whitespace(" ".join(tokens[after:]))
        if not description:
            continue
        value = _southside_money(amount.group(1))
        if value is None:
            continue
        signed = round(abs(value) * sign, 2)
        txns.append(Transaction(
            date=day,
            description=description,
            amount=signed,
            direction="credit" if signed > 0 else "debit",
        ))
    return txns


def _summary_identity_holds(stmt: Statement, txns: list[Transaction]) -> bool:
    """Detail matches every printed summary figure (counts, totals, balances)."""
    required = (
        stmt.beginning_balance,
        stmt.ending_balance,
        stmt.stated_credit_count,
        stmt.stated_debit_count,
        stmt.stated_total_credits,
        stmt.stated_total_debits,
    )
    if any(value is None for value in required):
        return False
    credits = [txn for txn in txns if txn.amount > 0]
    debits = [txn for txn in txns if txn.amount < 0]
    return (
        len(credits) == stmt.stated_credit_count
        and len(debits) == stmt.stated_debit_count
        and abs(sum(t.amount for t in credits) - stmt.stated_total_credits) <= 0.01
        and abs(abs(sum(t.amount for t in debits)) - stmt.stated_total_debits) <= 0.01
        and abs(
            stmt.beginning_balance + sum(t.amount for t in txns) - stmt.ending_balance
        ) <= 0.01
    )


def _repair_checks_from_image_captions(
    markdown: str, txns: list[Transaction], stmt: Statement
) -> list[Transaction]:
    """Correct OCR-misread check amounts from the check-image captions.

    Generic, evidence-gated (R-1 item 1 - replaces a repair keyed to one
    literal date/check/amount): the statement's own check-image captions
    ("Number: N  Date: m/d/yyyy  Amount: $X") are independent in-document
    evidence. A parsed "Check N" row is corrected to its caption amount only
    when (a) the printed summary identity currently fails, (b) the caption
    matches the row's check number AND date but disagrees on amount, and
    (c) applying the corrections makes the summary identity hold exactly.
    """
    captions: dict[tuple[str, str], float] = {}
    for check_no, raw_date, amount in _CHECK_CAPTION_RE.findall(markdown):
        try:
            captions[(check_no, _iso(raw_date))] = _money(amount)
        except ValueError:
            continue
    if not captions or _summary_identity_holds(stmt, txns):
        return txns

    repaired: list[Transaction] = []
    changed = False
    for txn in txns:
        match = re.fullmatch(r"Check (\d+)", txn.description)
        caption_amount = captions.get((match.group(1), txn.date)) if match else None
        if caption_amount is not None and abs(abs(txn.amount) - caption_amount) > 0.01:
            corrected = round(abs(caption_amount), 2)
            repaired.append(
                txn.model_copy(
                    update={"amount": -corrected if txn.amount < 0 else corrected}
                )
            )
            changed = True
        else:
            repaired.append(txn)
    if changed and _summary_identity_holds(stmt, repaired):
        return repaired
    return txns


def _parse_southside_checks(
    block: str, *, year: int, period: tuple[str, str], posted: frozenset[str]
) -> list[Transaction]:
    """`date  check-number  amount`, two or three of them to a printed line."""
    txns: list[Transaction] = []
    for raw_date, check_no, amount in re.findall(
        r"([A-Za-z0-9/]{2,5})\s+(\d{3,})\s*\*?\s+(" + _SS_MONEY + r")", block
    ):
        day = _southside_day(raw_date, period)
        if day is None:
            continue
        if not re.fullmatch(r"\d{1,2}/\d{1,2}", raw_date) and day not in posted:
            continue
        value = _southside_money(amount)
        if value is None:
            continue
        txns.append(Transaction(
            date=day,
            description=f"Check {check_no}",
            amount=round(-abs(value), 2),
            direction="debit",
        ))
    return txns


def parse_apex_scanned_statement(markdown: str) -> Statement | None:
    # Structural gates only: the bank's product name plus this layout's
    # summary phrasing (R-1 item 2 - the customer-name gate is gone).
    if not detect_apex(markdown).claims:
        return None
    markdown = normalize_mojibake(markdown)
    upper = markdown.upper()

    source = re.sub(r"(?<=\d)\.(?=\d{3}\.\d{2}\b)", ",", markdown)
    text = compact_whitespace(source)
    holder = _extract_holder_name(markdown)
    stmt = Statement(bank="Apex Bank", account_name=holder, currency="USD",
                     currency_source="institution_default")
    acct = re.search(r"Account Number:\s*([*%A-Z0-9]+)", text, re.IGNORECASE)
    if acct:
        stmt.account_number = acct.group(1)
    sm = re.search(
        r"Balance Forward From\s+(?P<start>\d{2}/\d{2}/\d{4})\s+(?P<begin>\d[\d,]*\.\d{2}).*?"
        r"(?P<credit_count>\d+)\s+Deposits/Credits.*?(?P<credits>\d[\d,]*\.\d{2})\s+\+.*?"
        r"Minimum Balance.*?(?P<min>\d[\d,]*\.\d{2}).*?"
        r"(?P<debit_count>\d+)\s+Withdrawals/Debits.*?(?P<debits>\d[\d,]*\.\d{2})\s+-.*?"
        r"Average Balance.*?(?P<avg>\d[\d,]*\.\d{2}).*?"
        r"Ending Balance As Of\s+(?P<end>\d{2}/\d{2}/\d{4})\s+(?P<ending>\d[\d,]*\.\d{2}).*?"
        r"Interest Paid This Period.*?(?P<interest>\d[\d,]*\.\d{2}).*?"
        r"Days In Earnings Period.*?(?P<days>\d+)",
        text,
        re.IGNORECASE,
    )
    if not sm:
        return None
    stmt.period_start = _iso(sm.group("start"))
    stmt.period_end = _iso(sm.group("end"))
    stmt.beginning_balance = _money(sm.group("begin"))
    stmt.ending_balance = _money(sm.group("ending"))
    stmt.days_in_period = int(sm.group("days"))
    stmt.stated_credit_count = int(sm.group("credit_count"))
    stmt.stated_debit_count = int(sm.group("debit_count"))
    stmt.stated_total_credits = _money(sm.group("credits"))
    stmt.stated_total_debits = _money(sm.group("debits"))
    printed_average = _money(sm.group("avg"))
    stmt.bank_reported_average_balance = printed_average
    stmt.bank_reported_average_label = (
        "Average Balance" if printed_average is not None else None
    )
    stmt.stated_interest_paid = _money(sm.group("interest"))
    deposits = _section(
        source,
        r"DATE AMOUNT DESCRIPTION\s+DATE AMOUNT DESCRIPTION",
        r"OTHER CREDITS",
    )
    credits = _section(
        source,
        r"OTHER CREDITS.*?DATE AMOUNT DESCRIPTION",
        r"CHECK NO DATE AMOUNT CHECK NO DATE AMOUNT",
    )
    checks = _section(
        source,
        r"CHECK NO DATE AMOUNT CHECK NO DATE AMOUNT",
        r"[^\n]*denotes missing check[^\n]*",
    )
    debits = _section(
        source,
        r"[^\n]*denotes missing check[^\n]*",
        r"SERVICE CHARGES",
    )
    if holder:
        # Continuation pages repeat the holder's header block up to the
        # re-printed column header; scrub it using the holder name extracted
        # from the document itself (R-1 item 2 - no memorized name).
        debits = re.sub(
            r"\s*--- Page \d+ ---\s+" + re.escape(holder) + r".*?DATE AMOUNT DESCRIPTION\s*",
            "\n",
            debits,
            flags=re.IGNORECASE | re.DOTALL,
        )
    service = _section(
        source,
        r"SERVICE CHARGES.*?DATE AMOUNT DESCRIPTION",
        r"S[EF]RVICE CHARGE ANALY",
    )
    fees = _section(
        source,
        r"FEES\s*CHARGED.*?DATE AMOUNT DESCRIPTION",
        r"TOTAL FEES",
    )

    txns: list[Transaction] = []
    txns.extend(_parse_two_column_date_amount_desc(deposits, sign=1))
    txns.extend(_parse_date_amount_description_rows(credits, sign=1))
    txns.extend(_parse_checks(checks, sign=-1))
    txns.extend(_parse_date_amount_description_rows(debits, sign=-1))
    txns.extend(_parse_date_amount_description_rows(service, sign=-1))
    txns.extend(_parse_date_amount_description_rows(fees, sign=-1))
    txns = _repair_checks_from_image_captions(source, txns, stmt)
    txns = _attach_daily_balances(_sort_txns(txns), _daily_balances(source))
    txns = _discard_inconsistent_ocr_balances(stmt, txns)
    # Completeness against the statement's own printed counts, not a magic
    # threshold (R-1 item 3 - was `len(txns) < 20`).
    stated_rows = (stmt.stated_credit_count or 0) + (stmt.stated_debit_count or 0)
    if stated_rows == 0 or len(txns) < stated_rows:
        return None
    stmt.transactions = txns
    return stmt


# ---------------------------------------------------------------------------
# Texas First Bank, photographed: the four-way partition whose split is not
# printed anywhere (W3 §SCANNEXT)
# ---------------------------------------------------------------------------
#
# The template prints a summary that states BOTH counts and BOTH totals, then
# spends the rest of the statement on four separately-headed grids::
#
#     Summary of Activity Since Your Last Statement
#       Beginning Balance   m/d/yy   b0
#       Deposits / Misc Credits    N   C
#       Withdrawals / Misc Debits  M   D
#     ** Ending Balance     m/d/yy   b1 **
#
#     Deposits and Other Credits      date  amount  description
#     Debits and Other Withdrawals    date  amount  description
#     ATM /POS Transactions           date  DEPOSITS | WITHDRAWALS  location
#     Checks                          three (date, check no, amount) columns
#     Daily Balance Summary           three (date, balance) columns
#
# **The ATM/POS grid is the whole difficulty.** It has TWO money columns —
# deposits and withdrawals — and the scan destroys the only thing that says
# which column a figure sat in: Tesseract collapses the run of spaces, so
# `4/07 300.00 ATM Withdrawal` and `4/16 300.00 ATM Cash Deposit` arrive as the
# same shape. The direction is therefore NOT read off the row.
#
# Neither is it guessed from the words. `ATM Cash Deposit`, `ATM Withdrawal`,
# `Debit Transfer`, `POS Purchase Non-PIN`, `POS Purchase with PIN` are five of
# this family's wordings and a sixth statement is free to print a seventh; a
# reader that memorised them would be reading its own list rather than the
# document, and `Debit Transfer` — the most common of them — is a WITHDRAWAL on
# one row and the deposit leg of a peer-to-peer transfer on another.
#
# The direction is SOLVED from arithmetic the bank prints twice, and the
# solution is checked against a third printing:
#
# 1. **The aggregate.** The summary's counts and totals cover the ATM grid too,
#    so what the grid contributes to each side is fixed by subtraction::
#
#        ATM deposits    = (N - rows in Deposits, C - total of Deposits)
#        ATM withdrawals = (M - rows in Debits - rows in Checks,
#                           D - total of Debits - total of Checks)
#
#    Both sides must come out non-negative, and their counts and totals must
#    add back to the grid's own row count and total. That is a statement about
#    the grids' COMPLETENESS - it is what catches the row Tesseract dropped -
#    and it is checked before the walk because it is cheap.
#
# 2. **The day.** `Daily Balance Summary` prints the end-of-day balance for
#    every day the account moved, so each day's NET is known before any ATM row
#    is directed. The day's ATM rows admit one sign assignment reproducing that
#    net — and this reader requires it to be UNIQUE (:func:`_tf_unique_subset`).
#    Two assignments reaching the same net differ by which row is the deposit,
#    and publishing either would be publishing a direction the document does
#    not determine. Ambiguity refuses the document.
#
# 3. **The closing identity**, `b0 + C - D == b1`, checked first because it is
#    one line of arithmetic on figures already in hand and it rejects a
#    mis-read summary before a grid is parsed. It is a fail-fast, not
#    independent evidence: once (1) and (2) hold it follows.
#
# **A negative balance prints its minus on the RIGHT** (the figure, then a
# space, then the hyphen), the same
# convention `analysis/balance_by_date.py` documents for its average-balance
# statistic. Three of the eight archive documents print at least one overdrawn
# day and one of them prints three; reading those as positive would publish a
# five-figure error into the ADB, so the trailing hyphen is part of the daily
# cell's grammar here and a LEADING minus is never a sign. The convention is
# not asserted — it is proven by the walk: on every document this reader
# publishes, every printed daily balance is reproduced to the cent, overdrawn
# days included.
#
# **Every daily cell must be legible.** A daily line carrying a residue that
# still contains digits after its cells are matched means the grid did not
# survive the scan, and the ADB is computed over that grid — so the document is
# refused rather than published with a hole. Measured on the archive: this
# refuses `9B3DB6CF...`, whose `5/22` cell Tesseract resolved as `714,71`
# (the decimal separator read as a comma). The ledger determines that day's
# balance as `714.71` exactly, so the printing is recoverable in principle —
# recorded in W3 §SCANNEXT as a card, not repaired here, because the repair
# needs its own evidence gate and this reader's contract is that the grid it
# publishes is the grid the bank printed.
#
# The issuer IS named on the page (unlike the core-processor templates), so
# `Statement.bank` carries it.

#: A printed figure on this template: always two decimals. Bounded on both
#: sides so a reference number cannot supply the head of one.
_TF_FIGURE = r"(?<![\d.,])\d[\d,]{0,15}\.\d{2}(?![\d,]*\d)"
#: A posting date inside the grids: month and day only, the year is the
#: period's (see :func:`_tf_iso`).
_TF_MD = r"\d{1,2}/\d{1,2}"

_TF_SECTION_RE = re.compile(
    r"^(?:(?P<credits>Deposits and Other Credits)"
    r"|(?P<debits>Debits and Other Withdrawals)"
    r"|(?P<atm>ATM\s*/\s*POS\s+Transactions)"
    r"|(?P<checks>Checks)"
    r"|(?P<daily>Daily Balance Summary))\s*$",
    re.IGNORECASE,
)
_TF_PAGE_RE = re.compile(r"^---\s*Page\s+\d+")
_TF_COLUMN_HEAD_RE = re.compile(r"^Date\b", re.IGNORECASE)
_TF_DETAIL_RE = re.compile(rf"^({_TF_MD})\s+({_TF_FIGURE})\s+(\S.*)$")
#: One cell of the three-column check grid. The check number is optional
#: because the scan loses it on some rows, and the `*` the bank prints for a
#: break in check-number sequence may arrive with or without a number.
_TF_CHECK_CELL_RE = re.compile(rf"({_TF_MD})\s+(?:(\d{{2,7}})\s*\*?\s+|\*\s+)?({_TF_FIGURE})")
#: One cell of the three-column daily grid, with the right-hand minus.
_TF_DAILY_CELL_RE = re.compile(rf"({_TF_MD})\s+({_TF_FIGURE})\s*(-)?")

_TF_SUMMARY_BEGIN_RE = re.compile(
    rf"Beginning Balance\s+(\d{{1,2}}/\d{{1,2}}/\d{{2,4}})\s+({_TF_FIGURE})", re.IGNORECASE
)
_TF_SUMMARY_END_RE = re.compile(
    rf"Ending Balance\s+(\d{{1,2}}/\d{{1,2}}/\d{{2,4}})\s+({_TF_FIGURE})", re.IGNORECASE
)
_TF_SUMMARY_CREDITS_RE = re.compile(
    rf"Deposits\s*/\s*Misc Credits\s+(\d{{1,6}})\s+({_TF_FIGURE})", re.IGNORECASE
)
_TF_SUMMARY_DEBITS_RE = re.compile(
    rf"Withdrawals\s*/\s*Misc Debits\s+(\d{{1,6}})\s+({_TF_FIGURE})", re.IGNORECASE
)
_TF_SERVICE_CHARGE_RE = re.compile(rf"^Service Charge\s+({_TF_FIGURE})\s*$", re.IGNORECASE | re.M)
#: The bank's own average, printed in WHOLE DOLLARS on this template. Evidence
#: only — `analysis/adb.py` owns the canonical figure (ADB doctrine).
_TF_AVERAGE_RE = re.compile(
    r"^Average Balance\s+(\d[\d,]{0,15}(?:\.\d{2})?)\s*$", re.IGNORECASE | re.M
)

TEXAS_FIRST_DETECTION_MARKERS = (
    # The issuer's own tele-banking domain, printed in the page furniture of
    # every page of the statement.
    required("tele_banking_domain", lambda t: "WWW.TEXASFIRST.BANK" in t),
    # This template's summary head.
    required("summary_head", lambda t: "SUMMARY OF ACTIVITY SINCE YOUR LAST STATEMENT" in t),
    # The grid this reader's day oracle is built on. Required at DETECTION and
    # not only at parse: a printing without it is not a document this reader
    # can direct the ATM grid on, and claiming it would strand it.
    required("daily_grid", lambda t: "DAILY BALANCE SUMMARY" in t),
)

detect_texas_first = make_detector(TEXAS_FIRST_DETECTION_MARKERS, detection_text)


def _tf_cents(token: str) -> int | None:
    value = parse_money(token.replace("$", "").strip())
    return None if value is None else int(round(value * 100))


def _tf_iso(mmdd: str, *, start: date, end: date) -> str | None:
    """The posting date's ISO form, or None when it is not inside the period.

    The grids print month and day only. The year comes from the printed period
    and from nowhere else: a date that lands outside it under either candidate
    year is a mis-read, and this returns None so the document fails closed
    rather than acquiring a transaction in the wrong year.

    A period spanning the new year has two candidate years, and AMBIGUITY IS
    REFUSED rather than resolved by picking one. That needs a period at least
    a year long to arise, which this template does not print — but "at least a
    year long" is a property of the DOCUMENT, and a mis-scanned period date is
    exactly how a one-month statement acquires one. Deciding it by iteration
    order (a set of two ints) would make the answer depend on nothing.
    """
    month_s, _, day_s = mmdd.partition("/")
    resolved: list[date] = []
    for year in sorted({start.year, end.year}):
        try:
            candidate = date(year, int(month_s), int(day_s))
        except ValueError:
            continue
        if start <= candidate <= end:
            resolved.append(candidate)
    return resolved[0].isoformat() if len(resolved) == 1 else None


def _tf_unique_subset(values: list[int], target: int) -> set[int] | None:
    """Indices of the ONE subset of `values` summing to `target`, else None.

    `values` are positive cent amounts and `target` is the deposit-side total
    the printed daily balance implies, so a subset is a direction assignment.
    Counting is capped at two: the question is not how many assignments exist
    but whether exactly one does, and a second one means the document does not
    determine the directions.
    """
    if target < 0 or target > sum(values):
        return None
    # sum -> (how many subsets reach it, capped at 2; one witness)
    states: dict[int, tuple[int, tuple[int, ...]]] = {0: (1, ())}
    for index, value in enumerate(values):
        nxt = dict(states)
        for reached, (count, witness) in states.items():
            moved = reached + value
            if moved > target:
                continue
            prior_count, prior_witness = nxt.get(moved, (0, ()))
            nxt[moved] = (
                min(2, prior_count + count),
                prior_witness if prior_count else witness + (index,),
            )
        states = nxt
        # A pathological day would make this exponential. The archive's widest
        # is eleven rows; refusing beyond a wide bound keeps a hostile document
        # from turning a parse into a hang.
        if len(states) > 100_000:
            return None
    count, witness = states.get(target, (0, ()))
    return set(witness) if count == 1 else None


class _TFRow:
    """One printed ledger row before its direction is known."""

    __slots__ = ("iso", "cents", "description")

    def __init__(self, iso: str, cents: int, description: str) -> None:
        self.iso, self.cents, self.description = iso, cents, description


def _tf_read_grids(markdown: str, *, start: date, end: date):
    """(credits, debits, atm, checks, daily) or None when a grid is illegible.

    `daily` is `[(iso, cents)]` in printed order. The section state resets at
    every page break: this template reprints each section's head after the page
    furniture, so a row can never be attributed to the section that ended on
    the previous page.
    """
    credits: list[_TFRow] = []
    debits: list[_TFRow] = []
    atm: list[_TFRow] = []
    checks: list[_TFRow] = []
    daily: list[tuple[str, int]] = []
    buckets = {"credits": credits, "debits": debits, "atm": atm}

    section: str | None = None
    pending: list[str] | None = None      # the open detail row's description
    open_row: _TFRow | None = None

    def close_row() -> None:
        nonlocal pending, open_row
        if open_row is not None and pending is not None:
            open_row.description = compact_whitespace(" ".join(pending))
        pending, open_row = None, None

    for raw in markdown.splitlines():
        line = raw.strip()
        if _TF_PAGE_RE.match(line):
            close_row()
            section = None
            continue
        head = _TF_SECTION_RE.match(line)
        if head is not None:
            close_row()
            section = head.lastgroup
            continue
        if section is None or not line:
            continue

        if section in buckets:
            row = _TF_DETAIL_RE.match(line)
            if row is not None:
                close_row()
                iso = _tf_iso(row.group(1), start=start, end=end)
                cents = _tf_cents(row.group(2))
                if iso is None or cents is None:
                    return None
                open_row = _TFRow(iso, cents, row.group(3).strip())
                pending = [row.group(3).strip()]
                buckets[section].append(open_row)
            elif pending is not None and not _TF_COLUMN_HEAD_RE.match(line):
                pending.append(line)
            continue

        # The two three-column grids. Their bodies are cells and nothing else,
        # so the first body line with no cell in it ends the grid — which is
        # what keeps the closing disclosure paragraph and its URL out of them.
        cells = list(
            (_TF_CHECK_CELL_RE if section == "checks" else _TF_DAILY_CELL_RE).finditer(line)
        )
        if not cells:
            if _TF_COLUMN_HEAD_RE.match(line):
                continue
            section = None
            continue
        residue = line
        for cell in reversed(cells):
            residue = residue[: cell.start()] + residue[cell.end():]
        if any(character.isdigit() for character in residue):
            # A cell that did not survive the scan. Both grids are oracles —
            # the check grid feeds the debit count, the daily grid feeds the
            # ADB — so an illegible cell fails the document closed.
            return None
        for cell in cells:
            iso = _tf_iso(cell.group(1), start=start, end=end)
            cents = _tf_cents(cell.group(3) if section == "checks" else cell.group(2))
            if iso is None or cents is None:
                return None
            if section == "checks":
                number = cell.group(2)
                checks.append(_TFRow(iso, cents, f"Check {number}" if number else "Check"))
            else:
                daily.append((iso, -cents if cell.group(3) else cents))
    close_row()
    return credits, debits, atm, checks, daily


def _tf_direct_atm(
    *,
    beginning: int,
    daily: list[tuple[str, int]],
    credits: list[_TFRow],
    debits: list[_TFRow],
    atm: list[_TFRow],
    checks: list[_TFRow],
) -> set[int] | None:
    """Indices of the ATM rows that are DEPOSITS, or None if not determined.

    Walks the printed daily balances in date order. Every day carrying a
    ledger row must have a printed balance (a day the grid does not mention is
    a day the grid lost), every printed balance must be reproduced exactly, and
    each day's ATM rows must admit exactly one sign assignment.
    """
    printed: dict[str, int] = {}
    for iso, balance in daily:
        if printed.setdefault(iso, balance) != balance:
            return None                      # the grid contradicts itself
    known: dict[str, int] = {}
    for row in credits:
        known[row.iso] = known.get(row.iso, 0) + row.cents
    for row in (*debits, *checks):
        known[row.iso] = known.get(row.iso, 0) - row.cents
    day_atm: dict[str, list[int]] = {}
    for index, row in enumerate(atm):
        day_atm.setdefault(row.iso, []).append(index)
    if set(known) - set(printed) or set(day_atm) - set(printed):
        return None

    deposits: set[int] = set()
    balance = beginning
    for iso in sorted(printed):
        target = printed[iso]
        residual = target - balance - known.get(iso, 0)
        indices = day_atm.get(iso, [])
        values = [atm[i].cents for i in indices]
        # sum(deposits) - sum(withdrawals) == residual, so the deposit side
        # totals (residual + everything) / 2.
        doubled = residual + sum(values)
        if doubled % 2:
            return None
        chosen = _tf_unique_subset(values, doubled // 2)
        if chosen is None:
            return None
        deposits.update(indices[i] for i in chosen)
        balance = target
    return deposits


def parse_texas_first_scanned_statement(markdown: str) -> Statement | None:
    if not detect_texas_first(markdown).claims:
        return None
    source = normalize_mojibake(markdown)

    begin = unique_match(source, _TF_SUMMARY_BEGIN_RE)
    end = unique_match(source, _TF_SUMMARY_END_RE)
    credit_summary = unique_match(source, _TF_SUMMARY_CREDITS_RE)
    debit_summary = unique_match(source, _TF_SUMMARY_DEBITS_RE)
    if not (begin and end and credit_summary and debit_summary):
        return None
    try:
        period_start = date.fromisoformat(_iso(begin.group(1)))
        period_end = date.fromisoformat(_iso(end.group(1)))
    except ValueError:
        return None
    if period_end < period_start:
        return None

    beginning_cents = _tf_cents(begin.group(2))
    ending_cents = _tf_cents(end.group(2))
    stated_credits = _tf_cents(credit_summary.group(2))
    stated_debits = _tf_cents(debit_summary.group(2))
    if None in (beginning_cents, ending_cents, stated_credits, stated_debits):
        return None
    stated_credit_count = int(credit_summary.group(1))
    stated_debit_count = int(debit_summary.group(1))
    # The fail-fast: a mis-read summary is rejected before a grid is parsed.
    if beginning_cents + stated_credits - stated_debits != ending_cents:
        return None

    grids = _tf_read_grids(source, start=period_start, end=period_end)
    if grids is None:
        return None
    credits, debits, atm, checks, daily = grids
    if not daily:
        return None

    # What the ATM grid has to contribute to each side, by subtraction from the
    # bank's own counts and totals.
    atm_credit_count = stated_credit_count - len(credits)
    atm_credit_cents = stated_credits - sum(row.cents for row in credits)
    atm_debit_count = stated_debit_count - len(debits) - len(checks)
    atm_debit_cents = stated_debits - sum(row.cents for row in debits) - sum(
        row.cents for row in checks
    )
    # Cheap arithmetic, run before the day walk, and the two halves are NOT
    # the same kind of check. Corrected after review found a counterexample to
    # the claim that both were redundant:
    #
    # * the COUNT half is LOAD-BEARING and nothing else in this reader can
    #   stand in for it. The walk is arithmetic over MONEY, so no printed
    #   balance constrains a count. A summary stating five debits over grids
    #   holding four — every total, the identity and every daily balance
    #   agreeing — passes every other gate here and publishes
    #   `stated_debit_count=5` beside four debit rows. Removing this line kills
    #   nothing else; it just publishes that document.
    # * the TOTAL half genuinely is redundant with the walk (a grid whose money
    #   does not add up cannot reproduce the printed daily balances either) and
    #   is kept as a fail-fast, so that a short grid is reported as a short
    #   grid rather than as "the day did not close".
    if min(atm_credit_count, atm_credit_cents, atm_debit_count, atm_debit_cents) < 0:
        return None
    if atm_credit_count + atm_debit_count != len(atm):
        return None
    if atm_credit_cents + atm_debit_cents != sum(row.cents for row in atm):
        return None

    deposit_indices = _tf_direct_atm(
        beginning=beginning_cents, daily=daily,
        credits=credits, debits=debits, atm=atm, checks=checks,
    )
    if deposit_indices is None:
        return None
    # The two readings of the same split, made to agree explicitly — and again
    # the two halves are not the same kind of check. An earlier version of this
    # comment called both "corroboration"; review supplied the counterexample
    # that makes the first half load-bearing.
    #
    # * the COUNT half is LOAD-BEARING. A summary counting ONE ATM deposit of
    #   100.00 against a grid whose `60.00` and `40.00` are uniquely both
    #   deposits agrees on every figure — the totals, the walk, the printed
    #   balance — and differs only in how many rows the money arrived in.
    #   Without this line that document publishes three credits against a
    #   stated credit count of two.
    # * the MONEY half is corroboration, and the derivation is worth keeping
    #   because it is what makes the count half's independence visible: summing
    #   the daily residuals gives `atm_credit_cents - atm_debit_cents`, and the
    #   aggregate total above gives their sum, so the deposit TOTAL is already
    #   fixed once every day has a unique assignment. The deposit COUNT is not
    #   fixed by anything.
    if len(deposit_indices) != atm_credit_count:
        return None
    if sum(atm[i].cents for i in deposit_indices) != atm_credit_cents:
        return None
    # The grid is printed in THREE COLUMNS, so its last CELL is not its last
    # DAY - taking reading position for chronology here would compare the
    # ending balance against whatever day sits at the foot of column three.
    last_day = max(iso for iso, _ in daily)
    if next(cents for iso, cents in daily if iso == last_day) != ending_cents:
        return None

    transactions: list[Transaction] = []
    for row in credits:
        transactions.append(Transaction(
            date=row.iso, description=row.description,
            amount=round(row.cents / 100, 2), direction="credit",
        ))
    for row in (*debits, *checks):
        transactions.append(Transaction(
            date=row.iso, description=row.description,
            amount=round(-row.cents / 100, 2), direction="debit",
        ))
    for index, row in enumerate(atm):
        credit = index in deposit_indices
        transactions.append(Transaction(
            date=row.iso, description=row.description,
            amount=round((row.cents if credit else -row.cents) / 100, 2),
            direction="credit" if credit else "debit",
        ))

    stmt = Statement(
        bank="Texas First Bank",
        account_name=_extract_holder_name(source),
        currency="USD",
        currency_source="institution_default",
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        beginning_balance=round(beginning_cents / 100, 2),
        ending_balance=round(ending_cents / 100, 2),
        stated_credit_count=stated_credit_count,
        stated_debit_count=stated_debit_count,
        stated_total_credits=round(stated_credits / 100, 2),
        stated_total_debits=round(stated_debits / 100, 2),
    )
    # `account_number` stays None: the CONSERVATIVE answer, not the only
    # possible one. Stated as measured, after review corrected an earlier
    # version of this comment that overclaimed.
    #
    # On the page-1 header the mask is what the scan destroys, on every archive
    # document of the class: `Account Number: FAKKAT AG`,
    # `Account Number: *AKKT BGO`. But it is NOT true that every surviving mask
    # elsewhere is a card. On one chain the account mask survives legibly -
    # `Account Number: ****7860` in a genuine statement header on page 13 of
    # one document, and `Account Number **** 7860` in the cheque-page headers
    # of four - and that IS the account; the card masks on those same documents
    # are `*****4975`, and on the other chain `*****5512` / `*****8152`.
    #
    # So the field could be recovered on four or five of the eight, from a
    # printing that is labelled and corroborated more than once. It is not
    # recovered HERE because doing it safely needs its own evidence gate (which
    # labelled occurrences count, and what to do when a document shows none),
    # and because publishing an account number on some documents of a family
    # and not others is a decision worth making deliberately. Carded for batch
    # 7 as ACCT-MASK-SCAN; until then honest-unknown, which is wrong about
    # nothing.
    service = unique_match(source, _TF_SERVICE_CHARGE_RE)
    if service is not None:
        charge = _tf_cents(service.group(1))
        if charge is not None:
            stmt.stated_service_charge = round(charge / 100, 2)
    average = unique_match(source, _TF_AVERAGE_RE)
    if average is not None:
        printed_average = parse_money(average.group(1))
        if printed_average is not None:
            # Evidence, never the platform's ADB: this template rounds its own
            # average to whole dollars, and `analysis/adb.py` owns the
            # canonical figure (ADB doctrine, 2026-08-15).
            stmt.bank_reported_average_balance = printed_average
            stmt.bank_reported_average_label = "Average Balance"
    # Published CHRONOLOGICALLY and DEDUPLICATED, not in printed order. The
    # grid is three columns wide, so its reading order is column-major and its
    # last cell is not its last day; and a day printed twice would reach
    # `analysis/adb.py` as a duplicate snapshot and cost the whole document its
    # `snapshot_dates_valid`. Deduplication is lossless here because a repeated
    # day whose balances DISAGREE has already refused the document
    # (:func:`_tf_direct_atm`), so the two entries are the same fact twice.
    stmt.stated_daily_balances = [
        StatementDailyBalance(date=iso, balance=round(cents / 100, 2))
        for iso, cents in sorted(dict(daily).items())
    ]
    stmt.transactions = _attach_daily_balances(
        _sort_txns(transactions), {iso: round(cents / 100, 2) for iso, cents in daily}
    )
    return stmt
