"""Shared, deterministic date handling for statement parsing.

Two jobs:

1. `parse_date` — one tolerant ISO/US date parser used by every downstream
   stage, so "2026-01-02", "01/02/2026" and "Jan 2, 2026" all resolve the
   same way no matter which parser produced the row.

2. `assign_transaction_years` — repair the calendar year on transactions when
   a statement period crosses a year boundary.

Why (2) is needed: most bank statements print transaction dates as MM/DD with
no year, so the per-bank parsers derive one year from the statement period
(typically `int(period_end[:4])`) and stamp it on every row. That is correct
for the ~97% of statements that sit inside a single year and silently wrong
for the rest. For a period of 2025-12-01 through 2026-01-02, a 12/15 row
becomes 2026-12-15 — six months in the future, outside the period, and it
would corrupt any chronological reconstruction built on top of it.

This module fixes it centrally rather than in each parser: the month and day
that the bank printed are preserved, and only the year is re-derived from the
statement period. One auditable rule, applied to every bank at once.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from .schema import Statement

_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%m/%d/%y",
    "%m-%d-%y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%b %d %Y",
    "%B %d %Y",
)


def parse_date(value: str | date | None) -> date | None:
    """Parse a statement date. Returns None rather than raising: a missing or
    unreadable date must not abort an entire statement."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    # Fast path: ISO, possibly with a time component appended.
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    for fmt in _FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _with_year(day: date, year: int) -> date | None:
    """Rebuild `day` in `year`, tolerating Feb 29 landing on a common year."""
    try:
        return date(year, day.month, day.day)
    except ValueError:
        return None


def resolve_year(
    month: int,
    day: int,
    period_start: date | None,
    period_end: date | None,
) -> int | None:
    """Pick the calendar year for a printed MM/DD within a statement period.

    A statement period spans at most ~2 months, so a given month/day belongs to
    exactly one of the period's candidate years in all but pathological cases.
    Preference order:

      1. the candidate year that places the date inside the period (earliest,
         if somehow both do)
      2. the month-sequence rule: months at or after the start month belong to
         the start year, earlier months belong to the end year
      3. the end year
    """
    if period_start is None and period_end is None:
        return None
    if period_start is None:
        return period_end.year
    if period_end is None:
        return period_start.year

    candidates = []
    for year in sorted({period_start.year, period_end.year}):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        candidates.append(candidate)

    inside = [c for c in candidates if period_start <= c <= period_end]
    if inside:
        return min(inside).year
    if period_start.year == period_end.year:
        return period_start.year
    # Outside the period (a check written before the period, say). Fall back to
    # the month sequence: Dec belongs to the opening year, Jan to the closing one.
    return period_start.year if month >= period_start.month else period_end.year


_MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTH_ALT = "|".join(_MONTH_ABBR)

# Posting-date tokens as banks print them at the head of a transaction row. Only
# matched at the start of a line, which is where a date column lands once the PDF
# is flattened to text — dates embedded in a description ("... 05-15-26 Apple.Com")
# are deliberately not matched.
_ROW_DATE_PATTERNS = (
    re.compile(rf"^\s*(?P<d>\d{{1,2}})\s+(?P<m>{_MONTH_ALT})[a-z]*\.?(?:\s+(?P<y>\d{{4}}))?\b", re.I),
    re.compile(rf"^\s*(?P<m>{_MONTH_ALT})[a-z]*\.?\s+(?P<d>\d{{1,2}})(?:\s*,?\s*(?P<y>\d{{4}}))?\b", re.I),
    re.compile(r"^\s*(?P<m>\d{1,2})[/-](?P<d>\d{1,2})(?:[/-](?P<y>\d{2,4}))?(?!\d)"),
    re.compile(r"^\s*(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})\b"),
)


def _row_date(line: str, period_start: date, period_end: date) -> date | None:
    for pattern in _ROW_DATE_PATTERNS:
        m = pattern.match(line)
        if not m:
            continue
        groups = m.groupdict()
        raw_month = groups.get("m") or ""
        if raw_month.isdigit():
            month = int(raw_month)
        else:
            month = _MONTH_ABBR.get(raw_month[:3].lower(), 0)
        day = int(groups["d"])
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return None
        if groups.get("y"):
            year = int(groups["y"])
            years = [year + 2000 if year < 100 else year]
        else:
            years = sorted({period_start.year, period_end.year})
        for year in years:
            try:
                candidate = date(year, month, day)
            except ValueError:
                continue
            if period_start <= candidate <= period_end:
                return candidate
        return None
    return None


# Lines that begin with a date but are NOT a posting row. Without these the
# guard misfires on almost every bank: statement-period headers, daily-balance
# summary grids and balance-label lines all start with a date.
#
# `total(s)? for` is the labelled form ("Total for this period"). The general
# section-total shape lives in `_SUMMARY_TOTAL_ROW` below.
_NOT_A_POSTING_ROW = re.compile(
    r"\b(through|statement period|beginning balance|opening balance|ending balance"
    r"|closing balance|previous balance|balance forward|average (daily |ledger |collected )?balance"
    r"|daily balance|total(s)? for|page\s*:?\s*\d+)\b",
    re.I,
)

# A printed section total that a bank dates in the Date column -- "Apr 30
# Closing totals 8,051.66 2,245.03" -- is a summary row, not a posting. Read as
# a posting it invents an activity day the statement never had, and the parser
# (correctly) produces no transaction for it, so `posting_dates_cover_source`
# fails for a reason that is not true of the document.
#
# Structure-keyed, not a bank wording: what makes this a total row is that the
# label ENDS in "total"/"totals" immediately before the money columns (or the
# end of the line) -- that is where a section total is printed, and it is not
# where a merchant name lands. A description that merely CONTAINS the word
# ("POS PURCHASE TOTAL WINE & MORE 45.00 1,200.00") keeps its posting date,
# because there the word is followed by more description rather than by money.
#
# Direction of effect: this can only REMOVE dates from `source_posting_dates`.
# `posting_dates_cover_source` is `source_dates - parsed_dates`, so a smaller
# source set can only shrink the missing set -- the check can go from failing
# to passing on a document, never from passing to failing.
_SUMMARY_TOTAL_ROW = re.compile(
    r"\btotals?\b[\s:.\-]*(?:\$?\(?-?\d[\d,]*\.\d{2}|$)",
    re.I,
)
#: MONEY PRESENCE, not money parsing: "is there an amount printed here?" Two
#: properties this pattern must have, both learned from documents:
#:
#: * a money figure prints exactly TWO decimals, so the right-hand digit bound
#:   is load-bearing. Without it `0.0000%` on an interest-rate line reads as
#:   the amount `0.00` and the proximity test below is satisfied by a rate.
#: * the decimal mark is a COMMA wherever the statement is printed in French,
#:   and the thousands separator is then a space (`1 234,56`). This module is
#:   shared by every bank in the archive, Canadian ones included; a
#:   presence test that only knows `1,234.56` reports "no money on this page"
#:   for a whole French statement and silently disables the checks below on
#:   exactly the documents whose column structure is hardest to read.
_MONEY_RE = re.compile(r"\d[\d, ]*[.,]\d{2}(?!\d)")
# The same printed section total, wrapped. Where the total's label and column
# captions fill the line, the bank's own date for that total is printed BELOW
# it, alone -- "Totals Amount Account balance as of" / "12/31/2025" /
# "-$70,195.36 $13,692.91". The bare date line then reaches the money-proximity
# test below, finds the total's figures on the next line, and is counted as a
# posting date the statement never had.
#
# Keyed on the label OPENING the line, and on that line carrying no money,
# which is what says the figures wrapped.
#
# Be honest about what each half buys, because the anchor is NOT a structural
# guarantee -- it is an archive-measured property. Censused over all 3,400
# readable documents: 1,355 of them (39.9%) print a moneyless line opening
# with "Total", 2,333 such lines in all. So the anchor alone does not isolate
# anything. What makes the rule precise is ADJACENCY: it is consulted only from
# the bare-date branch below, i.e. only when the very next line is nothing but
# a date token. That conjunction fires on 16 lines in 16 documents (0.5%) in
# the whole archive, all of them this one wrapped total row.
#
# The anchor still earns its place, on the other axis: unanchored, the same
# adjacency test also swallows genuine posting dates printed under a merchant
# called "Total Quality Logistics" and under the column headers
# "... FEES TOTAL*" and "Date Description Total Items ...". Those are measured
# too, and pinned in tests/test_adb.py.
#
# KNOWN FALSIFIER, since the rule cannot be proven from structure: a posting
# row whose DESCRIPTION opens with the word and prints no amount on its own
# line, sitting directly above a lone date -- "Total Wine & More" / "06/09" /
# the amounts. Its date is suppressed. No document in the surveyed archive
# prints that shape, and it is pinned as a test so the boundary is visible
# rather than implied.
#
# What keeps the falsifier tolerable is the direction of effect, which is the
# same as `_SUMMARY_TOTAL_ROW`: this can only REMOVE dates from
# `source_posting_dates`, and `posting_dates_cover_source` is
# `source_dates - parsed_dates`, so a document can go from failing to passing
# but never from passing to failing. The cost of being wrong is a coverage
# check that is quieter than it should be, never a false validation.
_WRAPPED_TOTAL_LABEL = re.compile(r"^totals?\b", re.I)
# A PAGE-HEADER POSITION RULE WAS TRIED HERE AND IS GONE (W3 §WITHHELDGRIDS
# WG12, closing the review's MAJOR-2). It refused a moneyless candidate found
# in the run of moneyless lines a `Page N of M` line opens, on the theory that
# a statement's masthead is identified by POSITION rather than by its wording,
# which is customer data. The theory is sound; the rule was not. It fired
# BEFORE the money lookahead below and was not conditioned on it, so a genuine
# posting row printed under a page break lost its date whenever its amount was
# printed on the next line but one. Two measurements decided it:
#
# * required to defer to that lookahead — the ruling's own remedy — the refusal
#   becomes UNREACHABLE, because the lookahead is asked of every moneyless
#   candidate and already refuses everything the position rule would have. The
#   deferring form was built and measured against its own ablation over the
#   2,558 archive documents the run of record resolves: identical on all of
#   them;
# * left as it was, it removed a printed posting day that the document's own
#   LEDGER posts on 16 of those documents
#   (`tools/withheldgrids_srcdates_audit.py`), which is the evidence loss the
#   removal-only argument is supposed to make impossible.
#
# What it bought was one document whose masthead date is the printed period
# boundary; that document is withheld again and named in WG12. The two shapes
# it got wrong are pinned in tests/test_adb.py so the boundary stays visible.
#: A table's own column caption. A line that names a date column AND a money
#: column while carrying no money is announcing the table that FOLLOWS it, so
#: money printed after it belongs to that table's first row and not to
#: whatever was printed above the caption. Used to bound the money-proximity
#: lookahead below.
_COLUMN_CAPTION_DATE = re.compile(r"\bdate\b", re.I)
_COLUMN_CAPTION_MONEY = re.compile(
    r"\b(?:amount|balance|debit|credit|withdrawal|deposit)s?\b", re.I
)
#: Dot leaders are typographic filler, not content. One issuer prints its
#: daily-balance block as `.......... DAILY BALANCE` and its grid caption as
#: `Date.......................................Balance`, so the section
#: heading below never matches and the grid's rows are read as postings of the
#: account whose ledger the statement publishes.
_DOT_LEADERS = re.compile(r"\.{3,}")
# A date-token grid ("01/01 -225.43 01/12 4.68 01/22 -14.82") is a balance
# summary, not a posting row: real posting rows carry one date, not several.
_DATE_TOKEN_RE = re.compile(
    rf"(?<!\d)(?:\d{{1,2}}[/-]\d{{1,2}}(?:[/-]\d{{2,4}})?|\d{{1,2}}\s+(?:{_MONTH_ALT})[a-z]*"
    rf"|(?:{_MONTH_ALT})[a-z]*\.?\s+\d{{1,2}})(?!\d)",
    re.I,
)

_DAILY_BALANCE_SECTION_START = re.compile(
    r"^\s*(?:daily balances?|daily balance (?:summary|history)|balance by date"
    #: The grid's COLUMN CAPTION, for the layouts that print no heading above
    #: it. Two words and nothing else on the line is a caption, not a row.
    r"|date\s+balance)\s*$",
    re.I,
)
_DAILY_BALANCE_SECTION_END = re.compile(
    r"^\s*(?:overdraft|returned item|checks?|deposits?|withdrawals?|transactions?|"
    r"service charges?|fees?|account summary|page\b)",
    re.I,
)


def _is_posting_row(line: str) -> bool:
    if _NOT_A_POSTING_ROW.search(line):
        return False
    if _SUMMARY_TOTAL_ROW.search(line):
        return False
    return len(_DATE_TOKEN_RE.findall(line)) <= 1


def _is_column_caption(line: str) -> bool:
    """Does this line announce a table rather than print a row of one?"""
    return (
        not _MONEY_RE.search(line)
        and bool(_COLUMN_CAPTION_DATE.search(line))
        and bool(_COLUMN_CAPTION_MONEY.search(line))
    )


def _without_leaders(line: str) -> str:
    return _DOT_LEADERS.sub(" ", line) if ".." in line else line


def source_posting_dates(markdown: str, period_start: date, period_end: date) -> set[date]:
    """Posting dates the SOURCE statement prints, within the statement period.

    Used to prove a parser did not silently fold several posting dates into one.
    That failure mode is invisible to arithmetic checks — misdated rows still sum
    to the right totals and still reconcile to the closing balance — but it
    corrupts the daily ledger and therefore Average Daily Balance.

    Only leading date tokens on lines that look like a posting row count; period
    headers, balance-summary grids, balance labels and printed section totals
    are excluded, because treating those as posting dates would flag almost
    every clean statement.

    This is a heuristic over text whose column structure the PDF flattening has
    already destroyed, so it is tuned to be quiet rather than exhaustive: across
    the 101-statement corpus it produces no false positives, at the cost of
    possibly missing a collapsed date on a layout not represented there. A bare
    date line sitting immediately above an unrelated posting row can still be
    counted, since the money-proximity test cannot tell the two apart.

    THE QUIETING IS ONE-DIRECTIONAL, and that is what makes each rule below
    safe to add. `posting_dates_cover_source` is `source_dates - parsed_dates`,
    so removing a date can only take a document from failing to passing, never
    the reverse: the cost of being wrong is a check that is quieter than it
    should be, never a false validation. Widening the corpus beyond the 101
    found five printed shapes that open with a date and are not posting rows —
    an interest-rate line, a page-header masthead, a Beginning/Ending Balance
    row whose label is printed on the NEXT line, a marketing sentence, and a
    second account's dot-leadered daily-balance grid. Each is refused by
    structure below, and each refusal is pinned together with the thing it must
    not touch (W3 §WITHHELDGRIDS).

    Layout-aware native extractors can provide a scoped
    `SOURCE_POSTING_DATES_BEGIN` block. That authoritative source list takes
    precedence over the fallback heuristic, avoiding dates from other accounts
    in the same PDF.
    """
    lines = markdown.splitlines()
    if "SOURCE_POSTING_DATES_BEGIN" in lines:
        found: set[date] = set()
        inside = False
        for line in lines:
            if line == "SOURCE_POSTING_DATES_BEGIN":
                inside = True
                continue
            if line == "SOURCE_POSTING_DATES_END":
                break
            if not inside or not line.startswith("SOURCE_POSTING_DATE|"):
                continue
            parsed = _row_date(line.split("|", 1)[1], period_start, period_end)
            if parsed is not None:
                found.add(parsed)
        return found

    found: set[date] = set()
    in_daily_balance_section = False
    for index, line in enumerate(lines):
        if _DAILY_BALANCE_SECTION_START.match(_without_leaders(line)):
            in_daily_balance_section = True
            continue
        if in_daily_balance_section:
            if _DAILY_BALANCE_SECTION_END.match(line):
                in_daily_balance_section = False
            else:
                continue
        if not _is_posting_row(line):
            continue
        parsed = _row_date(line, period_start, period_end)
        if parsed is None:
            continue
        # Some banks print the date alone on its own line (Navy Federal), which is
        # a genuine posting row; but so do page headers and section breaks. Require
        # a money amount close by to tell them apart.
        match = next(p.match(line) for p in _ROW_DATE_PATTERNS if p.match(line))
        remainder = line[match.end():].strip()
        # Chase card rows can begin with the card's purchase date followed only
        # by a masked card suffix. That is not the account posting date.
        if re.fullmatch(r"\(\s*\.\.\.\s*\d+\s*\)", remainder):
            continue
        # A summary block can print a balance label with the DATE as the
        # label's own qualifier -- "AUG 31 BALANCE" -- so none of the compound
        # wordings in `_NOT_A_POSTING_ROW` ("closing balance", "opening
        # balance") ever forms and the label reads as a posting row. What
        # identifies it is that the whole remainder is the bare word, with no
        # money on the line: a posting row's remainder is a description, and a
        # layout that labels a balance this way prints its figure elsewhere.
        #
        # Direction of effect, as for `_SUMMARY_TOTAL_ROW`: this can only
        # REMOVE dates from `source_posting_dates`, and
        # `posting_dates_cover_source` is `source_dates - parsed_dates`, so the
        # check can go from failing to passing on a document, never the reverse.
        if re.fullmatch(r"balances?", remainder, re.I) and not _MONEY_RE.search(line):
            continue
        if not _MONEY_RE.search(line):
            if len(remainder) < 3:
                previous = next(
                    (l.strip() for l in reversed(lines[:index]) if l.strip()), ""
                )
                if _WRAPPED_TOTAL_LABEL.match(previous) and not _MONEY_RE.search(previous):
                    continue
                # THE COLUMN-PER-LINE LAYOUT. Where the flattening puts each
                # cell on its own line, a row's DESCRIPTION is the next line
                # rather than this one, so the labels that
                # `_NOT_A_POSTING_ROW` refuses on a flattened row never reach
                # it: `Beginning Balance` and `Ending Balance` are printed
                # under their own date and are counted as activity days the
                # statement never had. Read the description where this layout
                # prints it. Mirror of the wrapped-total lookback above.
                following = next(
                    (l.strip() for l in lines[index + 1:] if l.strip()), ""
                )
                if _NOT_A_POSTING_ROW.search(following) or _SUMMARY_TOTAL_ROW.search(
                    following
                ):
                    continue
            # A posting row prints an amount: on the row, or — in the
            # column-per-line layout — within the next few lines. Requiring
            # it of EVERY moneyless candidate is what refuses a marketing
            # sentence that opens with a date ("June 15 is ... Day, and now is
            # a great time to ...") without needing to recognise prose — and,
            # since the page-header position rule above was withdrawn, it is
            # also the only thing that refuses a masthead. The lookahead stops
            # at a column caption because money printed after a caption belongs
            # to the table the caption announces.
            lookahead: list[str] = []
            for candidate in lines[index + 1: index + 5]:
                if not candidate.strip():
                    continue
                if _is_column_caption(candidate):
                    break
                lookahead.append(candidate)
                if len(lookahead) == 3:
                    break
            if not any(_MONEY_RE.search(l) for l in lookahead):
                continue
        found.add(parsed)
    return found


def assign_transaction_years(stmt: Statement) -> Statement:
    """Re-derive transaction years from the statement period.

    Only touches statements whose period crosses a year boundary, and only
    changes the year — the bank-printed month and day are authoritative and are
    never modified. A no-op for single-year periods, which is the common case.
    """
    period_start = parse_date(stmt.period_start)
    period_end = parse_date(stmt.period_end)
    if period_start is None or period_end is None:
        return stmt
    if period_start.year == period_end.year:
        return stmt

    changed = False
    transactions = []
    for txn in stmt.transactions:
        parsed = parse_date(txn.date)
        if parsed is None:
            transactions.append(txn)
            continue
        year = resolve_year(parsed.month, parsed.day, period_start, period_end)
        if year is None or year == parsed.year:
            transactions.append(txn)
            continue
        corrected = _with_year(parsed, year)
        if corrected is None:
            transactions.append(txn)
            continue
        changed = True
        transactions.append(txn.model_copy(update={"date": corrected.isoformat()}))

    if not changed:
        return stmt
    return stmt.model_copy(update={"transactions": transactions})
